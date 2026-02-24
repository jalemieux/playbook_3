# Intent-to-Action Eval Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend eval.py to measure how well 7 LLM models translate user intent into executable Linux actions, scored by an LLM judge.

**Architecture:** Single-shot LiteLLM calls per (model, prompt) pair, then a judge model scores each response against weighted criteria. Results written as markdown with summary leaderboard.

**Tech Stack:** Python, LiteLLM, pytest, PyYAML

**Design doc:** `docs/plans/2026-02-24-intent-to-action-eval-design.md`

---

### Task 1: Update system prompt to Ubuntu

**Files:**
- Modify: `src/agent.py:6` (SYSTEM_PROMPT)
- Test: `tests/test_agent.py` (verify no tests break)

**Step 1: Change "macOS" to "Ubuntu" in SYSTEM_PROMPT**

In `src/agent.py`, line 6, change:
```python
SYSTEM_PROMPT = """You are a personal assistant. You have one tool: execute_bash. Use it to accomplish tasks on the user's computer. You are running on macOS.
```
to:
```python
SYSTEM_PROMPT = """You are a personal assistant. You have one tool: execute_bash. Use it to accomplish tasks on the user's computer. You are running on Ubuntu.
```

**Step 2: Run existing tests to verify nothing breaks**

Run: `pytest tests/test_agent.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add src/agent.py
git commit -m "chore: update system prompt from macOS to Ubuntu"
```

---

### Task 2: Add `format_response()` helper

**Files:**
- Modify: `eval.py`
- Test: `tests/test_eval.py`

**Step 1: Write the failing test**

Add to `tests/test_eval.py`:
```python
def test_format_response_text_only():
    """format_response returns content when no tool calls."""
    from eval import format_response
    result = {"content": "Hello there!", "tool_calls": None}
    assert format_response(result) == "Hello there!"


def test_format_response_with_tool_calls():
    """format_response includes tool call details."""
    from eval import format_response
    result = {
        "content": "I'll set that up for you.",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "execute_bash",
                    "arguments": '{"command": "crontab -e"}',
                },
            }
        ],
    }
    text = format_response(result)
    assert "I'll set that up for you." in text
    assert "execute_bash" in text
    assert "crontab -e" in text
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval.py::test_format_response_text_only tests/test_eval.py::test_format_response_with_tool_calls -v`
Expected: FAIL with ImportError (format_response doesn't exist)

**Step 3: Implement format_response**

Add to `eval.py` after imports:
```python
import json

def format_response(result: dict) -> str:
    """Format LLM response (content + tool_calls) as readable text."""
    parts = []
    if result.get("content"):
        parts.append(result["content"])
    if result.get("tool_calls"):
        for tc in result["tool_calls"]:
            fn = tc["function"]
            args = json.loads(fn["arguments"])
            parts.append(f"[Tool call: {fn['name']}({json.dumps(args)})]")
    return "\n".join(parts) if parts else "[no response]"
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval.py::test_format_response_text_only tests/test_eval.py::test_format_response_with_tool_calls -v`
Expected: PASS

**Step 5: Commit**

```bash
git add eval.py tests/test_eval.py
git commit -m "feat(eval): add format_response helper for readable LLM output"
```

---

### Task 3: Replace `run_single()` with single-shot LiteLLM call

**Files:**
- Modify: `eval.py` (run_single)
- Test: `tests/test_eval.py`

**Step 1: Write the failing test**

Replace `test_run_single` and `test_run_single_error` in `tests/test_eval.py`:
```python
def test_run_single():
    """run_single makes a single-shot LiteLLM call and returns structured result."""
    from eval import run_single, EVAL_SYSTEM_PROMPT
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "I'll do that."
    mock_response.choices[0].message.tool_calls = None

    with patch("eval.litellm.completion", return_value=mock_response) as mock_comp:
        result, elapsed = run_single("Hello", "test/model-1")

    assert result["content"] == "I'll do that."
    assert result["tool_calls"] is None
    assert elapsed >= 0
    # Verify it used the eval system prompt
    call_args = mock_comp.call_args
    messages = call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "Ubuntu" in messages[0]["content"]


def test_run_single_with_tool_calls():
    """run_single captures tool_calls from response."""
    from eval import run_single

    mock_tc = MagicMock()
    mock_tc.id = "call_1"
    mock_tc.type = "function"
    mock_tc.function.name = "execute_bash"
    mock_tc.function.arguments = '{"command": "ls"}'

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Let me check."
    mock_response.choices[0].message.tool_calls = [mock_tc]

    with patch("eval.litellm.completion", return_value=mock_response):
        result, elapsed = run_single("List files", "test/model-1")

    assert result["content"] == "Let me check."
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["function"]["name"] == "execute_bash"


def test_run_single_error():
    """run_single captures exceptions."""
    from eval import run_single

    with patch("eval.litellm.completion", side_effect=Exception("API down")):
        result, elapsed = run_single("Hello", "test/model-1")

    assert "ERROR" in result["content"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval.py::test_run_single tests/test_eval.py::test_run_single_with_tool_calls tests/test_eval.py::test_run_single_error -v`
Expected: FAIL

**Step 3: Rewrite run_single**

Replace `run_single` in `eval.py`:
```python
import litellm
from src.llm import TOOL_SCHEMA

EVAL_SYSTEM_PROMPT = """You are a personal assistant. You have one tool: execute_bash. Use it to accomplish tasks on the user's computer. You are running on Ubuntu.

When you receive a message:
- If it requires action, use bash to accomplish it.
- If it's conversational, just reply.
- If you're unsure what the user wants, ask.

Keep replies short and direct."""


def run_single(prompt_text: str, model: str) -> tuple[dict, float]:
    """Single-shot LLM call. Returns (result_dict, elapsed_seconds).

    result_dict has 'content' (str|None) and 'tool_calls' (list[dict]|None).
    """
    messages = [
        {"role": "system", "content": EVAL_SYSTEM_PROMPT},
        {"role": "user", "content": prompt_text},
    ]
    start = time.time()
    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            tools=[TOOL_SCHEMA],
            timeout=60,
        )
        message = response.choices[0].message
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
        result = {"content": message.content, "tool_calls": tool_calls}
    except Exception as e:
        result = {"content": f"ERROR: {e}", "tool_calls": None}
    elapsed = time.time() - start
    return result, elapsed
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval.py::test_run_single tests/test_eval.py::test_run_single_with_tool_calls tests/test_eval.py::test_run_single_error -v`
Expected: PASS

**Step 5: Commit**

```bash
git add eval.py tests/test_eval.py
git commit -m "refactor(eval): switch run_single to single-shot LiteLLM call"
```

---

### Task 4: Add `judge_single()` function

**Files:**
- Modify: `eval.py`
- Test: `tests/test_eval.py`

**Step 1: Write the failing test**

Add to `tests/test_eval.py`:
```python
def test_judge_single():
    """judge_single sends response + criteria to judge model and parses scores."""
    from eval import judge_single

    judge_response_json = json.dumps({
        "uses-scheduler": {"score": 1.0, "reasoning": "Uses crontab"},
        "correct-schedule": {"score": 0.5, "reasoning": "Close but not exact"},
    })
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = judge_response_json

    criteria = [
        {"name": "uses-scheduler", "weight": 3, "description": "Uses crontab"},
        {"name": "correct-schedule", "weight": 2, "description": "Correct cron"},
    ]

    with patch("eval.litellm.completion", return_value=mock_response):
        scores = judge_single(
            prompt_text="Set a reminder",
            response_text="I'll use crontab...",
            criteria=criteria,
            judge_model="test/judge-model",
        )

    assert scores["uses-scheduler"]["score"] == 1.0
    assert scores["correct-schedule"]["score"] == 0.5
    assert "reasoning" in scores["uses-scheduler"]


def test_judge_single_json_parse_error():
    """judge_single handles malformed JSON from judge."""
    from eval import judge_single

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is not JSON"

    criteria = [{"name": "test", "weight": 1, "description": "Test"}]

    with patch("eval.litellm.completion", return_value=mock_response):
        scores = judge_single("prompt", "response", criteria, "test/judge")

    # Should return zero scores on parse failure
    assert scores["test"]["score"] == 0.0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval.py::test_judge_single tests/test_eval.py::test_judge_single_json_parse_error -v`
Expected: FAIL

**Step 3: Implement judge_single**

Add to `eval.py`:
```python
JUDGE_SYSTEM_PROMPT = """You are evaluating an AI assistant's ability to translate user intent into executable Linux (Ubuntu) actions. The assistant has one tool: execute_bash.

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
}"""


def judge_single(prompt_text: str, response_text: str, criteria: list[dict], judge_model: str) -> dict:
    """Score one response against criteria using the judge model.

    Returns {criterion_name: {"score": float, "reasoning": str}}.
    On JSON parse failure, returns zero scores for all criteria.
    """
    criteria_text = "\n".join(
        f"- {c['name']} (weight {c['weight']}): {c['description']}"
        for c in criteria
    )
    user_msg = (
        f"## User Request\n{prompt_text}\n\n"
        f"## Assistant Response\n{response_text}\n\n"
        f"## Criteria\n{criteria_text}"
    )
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    response = litellm.completion(model=judge_model, messages=messages, timeout=60)
    raw = response.choices[0].message.content

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return {c["name"]: {"score": 0.0, "reasoning": "Judge returned invalid JSON"} for c in criteria}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval.py::test_judge_single tests/test_eval.py::test_judge_single_json_parse_error -v`
Expected: PASS

**Step 5: Commit**

```bash
git add eval.py tests/test_eval.py
git commit -m "feat(eval): add judge_single for LLM-as-judge scoring"
```

---

### Task 5: Update `run_all()` and add `judge_all()`

**Files:**
- Modify: `eval.py`
- Test: `tests/test_eval.py`

**Step 1: Write the failing test**

Add to `tests/test_eval.py`:
```python
def test_run_all():
    """run_all runs every prompt × model and collects structured results."""
    from eval import run_all

    models = [{"name": "model-a", "model": "test/model-a"}]
    prompts = [{"name": "greet", "text": "Hello", "criteria": []}]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hi!"
    mock_response.choices[0].message.tool_calls = None

    with patch("eval.litellm.completion", return_value=mock_response):
        results = run_all(models, prompts)

    assert len(results) == 1
    assert results[0]["prompt_name"] == "greet"
    assert len(results[0]["model_results"]) == 1
    assert results[0]["model_results"][0]["result"]["content"] == "Hi!"


def test_judge_all():
    """judge_all scores all model results and computes weighted scores."""
    from eval import judge_all

    results = [
        {
            "prompt_name": "test",
            "prompt_text": "Do something",
            "model_results": [
                {
                    "model_name": "model-a",
                    "result": {"content": "Done", "tool_calls": None},
                    "formatted": "Done",
                    "elapsed": 1.0,
                }
            ],
        }
    ]
    prompts = [
        {
            "name": "test",
            "text": "Do something",
            "criteria": [
                {"name": "did-it", "weight": 2, "description": "Did the thing"},
                {"name": "quality", "weight": 1, "description": "Did it well"},
            ],
        }
    ]

    judge_scores = {
        "did-it": {"score": 1.0, "reasoning": "Yes"},
        "quality": {"score": 0.5, "reasoning": "Meh"},
    }
    with patch("eval.judge_single", return_value=judge_scores):
        scored = judge_all(results, prompts, "test/judge")

    mr = scored[0]["model_results"][0]
    assert mr["scores"] == judge_scores
    # Weighted: (1.0*2 + 0.5*1) / (2+1) = 2.5/3 ≈ 0.833
    assert abs(mr["weighted_score"] - 0.833) < 0.01
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval.py::test_run_all tests/test_eval.py::test_judge_all -v`
Expected: FAIL

**Step 3: Update run_all and add judge_all**

Replace `run_all` and add `judge_all` in `eval.py`:
```python
def run_all(models: list[dict], prompts: list[dict]) -> list[dict]:
    """Run every prompt against every model. Returns structured results."""
    results = []
    for prompt in prompts:
        prompt_results = {
            "prompt_name": prompt["name"],
            "prompt_text": prompt["text"],
            "model_results": [],
        }
        for model in models:
            print(f"  [{model['name']}] {prompt['name']}...", end=" ", flush=True)
            result, elapsed = run_single(prompt["text"], model["model"])
            formatted = format_response(result)
            print(f"{elapsed:.1f}s")
            prompt_results["model_results"].append({
                "model_name": model["name"],
                "result": result,
                "formatted": formatted,
                "elapsed": elapsed,
            })
        results.append(prompt_results)
    return results


def judge_all(results: list[dict], prompts: list[dict], judge_model: str) -> list[dict]:
    """Score all results using the judge model. Mutates and returns results."""
    prompt_lookup = {p["name"]: p for p in prompts}
    for entry in results:
        prompt = prompt_lookup[entry["prompt_name"]]
        criteria = prompt.get("criteria", [])
        if not criteria:
            continue
        for mr in entry["model_results"]:
            print(f"  Judging [{mr['model_name']}] {entry['prompt_name']}...", end=" ", flush=True)
            scores = judge_single(
                prompt["text"], mr["formatted"], criteria, judge_model
            )
            mr["scores"] = scores
            # Weighted average
            total_weight = sum(c["weight"] for c in criteria)
            weighted_sum = sum(
                scores.get(c["name"], {}).get("score", 0.0) * c["weight"]
                for c in criteria
            )
            mr["weighted_score"] = weighted_sum / total_weight if total_weight else 0.0
            print(f"{mr['weighted_score']:.2f}")
    return results
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval.py::test_run_all tests/test_eval.py::test_judge_all -v`
Expected: PASS

**Step 5: Commit**

```bash
git add eval.py tests/test_eval.py
git commit -m "feat(eval): update run_all for single-shot, add judge_all scoring"
```

---

### Task 6: Rewrite `write_report()` with summary table

**Files:**
- Modify: `eval.py`
- Test: `tests/test_eval.py`

**Step 1: Write the failing test**

Replace `test_write_report` in `tests/test_eval.py`:
```python
def test_write_report(tmp_path):
    """write_report generates markdown with summary table and per-prompt detail."""
    from eval import write_report

    results = [
        {
            "prompt_name": "test-prompt",
            "prompt_text": "Do something",
            "model_results": [
                {
                    "model_name": "model-a",
                    "result": {"content": "Done", "tool_calls": None},
                    "formatted": "Done",
                    "elapsed": 1.5,
                    "scores": {
                        "did-it": {"score": 1.0, "reasoning": "Yes"},
                    },
                    "weighted_score": 0.85,
                },
            ],
        }
    ]
    output = tmp_path / "report.md"
    write_report(results, output)
    text = output.read_text()
    assert "# Eval Results" in text
    assert "Summary" in text
    assert "model-a" in text
    assert "0.85" in text
    assert "did-it" in text
    assert "1.5s" in text
    assert "Done" in text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval.py::test_write_report -v`
Expected: FAIL (old write_report doesn't output scores)

**Step 3: Rewrite write_report**

Replace `write_report` in `eval.py`:
```python
def write_report(results: list[dict], output_path: Path) -> None:
    """Write a markdown comparison report with summary table and detail."""
    lines = [f"# Eval Results — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]

    # Summary table
    if results and results[0]["model_results"]:
        model_names = [mr["model_name"] for mr in results[0]["model_results"]]
        prompt_names = [r["prompt_name"] for r in results]

        lines.append("## Summary\n")
        header = "| Model | " + " | ".join(prompt_names) + " | Avg |"
        separator = "|---" + "|---" * len(prompt_names) + "|---|"
        lines.append(header)
        lines.append(separator)

        for model_name in model_names:
            scores = []
            for entry in results:
                mr = next((m for m in entry["model_results"] if m["model_name"] == model_name), None)
                score = mr.get("weighted_score", 0.0) if mr else 0.0
                scores.append(score)
            avg = sum(scores) / len(scores) if scores else 0.0
            row = f"| {model_name} | " + " | ".join(f"{s:.2f}" for s in scores) + f" | {avg:.2f} |"
            lines.append(row)
        lines.append("")

    # Per-prompt detail
    for entry in results:
        lines.append(f"## \"{entry['prompt_text']}\"\n")
        for mr in entry["model_results"]:
            score_str = f" — Score: {mr['weighted_score']:.2f}" if "weighted_score" in mr else ""
            lines.append(f"### {mr['model_name']}{score_str} ({mr['elapsed']:.1f}s)\n")

            if "scores" in mr:
                lines.append("**Criteria:**")
                for cname, cdata in mr["scores"].items():
                    lines.append(f"- {cname}: {cdata['score']:.1f} — {cdata['reasoning']}")
                lines.append("")

            lines.append(f"**Response:**\n{mr['formatted']}\n")
        lines.append("---\n")

    Path(output_path).write_text("\n".join(lines))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval.py::test_write_report -v`
Expected: PASS

**Step 5: Commit**

```bash
git add eval.py tests/test_eval.py
git commit -m "feat(eval): rewrite report with summary table and scored detail"
```

---

### Task 7: Update `main()` and `eval.yaml`

**Files:**
- Modify: `eval.py` (main function)
- Rewrite: `eval.yaml`

**Step 1: Update main() to wire everything together**

Replace `main()` in `eval.py`:
```python
def main():
    parser = argparse.ArgumentParser(description="Run eval across models")
    parser.add_argument("--config", default="eval.yaml", help="Eval config YAML")
    parser.add_argument("--output", default=None, help="Output markdown path")
    args = parser.parse_args()

    eval_cfg = load_eval_config(Path(args.config))

    output_path = args.output or f"results/{datetime.now().strftime('%Y-%m-%dT%H-%M')}.md"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    models = eval_cfg["models"]
    prompts = eval_cfg["prompts"]
    judge_model = eval_cfg["judge"]["model"]

    print(f"Running {len(prompts)} prompts × {len(models)} models\n")
    results = run_all(models, prompts)

    print(f"\nJudging with {judge_model}...\n")
    results = judge_all(results, prompts, judge_model)

    write_report(results, Path(output_path))
    print(f"\nReport saved to {output_path}")
```

**Step 2: Write new eval.yaml**

Write `eval.yaml` with the full config from the design doc (7 models, 5 prompts with criteria, judge section).

**Step 3: Run all tests**

Run: `pytest tests/test_eval.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add eval.py eval.yaml
git commit -m "feat(eval): wire up judge pipeline in main, add full eval config"
```

---

### Task 8: Clean up removed imports and old code

**Files:**
- Modify: `eval.py` (remove unused imports of handler, load_config)

**Step 1: Remove unused imports**

In `eval.py`, remove:
```python
from src.agent import handler
from src.config import load_config
```

The `build_agent_config` function is also no longer needed — remove it.

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS (update test_build_agent_config to be removed or skip)

**Step 3: Remove test_build_agent_config from tests**

Remove `test_build_agent_config` from `tests/test_eval.py` since `build_agent_config` no longer exists.

**Step 4: Run all tests again**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add eval.py tests/test_eval.py
git commit -m "chore(eval): remove unused imports and build_agent_config"
```

---

### Task 9: Update documentation

**Files:**
- Modify: `README.md` (eval section)
- Modify: `docs/architecture.md` (if exists, add eval components)

**Step 1: Update README with eval usage**

Add to the eval section of README:
- Updated `eval.yaml` format with judge + criteria
- How to run: `python eval.py`
- Output: scored markdown report in `results/`

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with scored eval framework usage"
```
