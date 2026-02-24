"""Lightweight eval framework — run prompts across models, compare results."""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

import litellm
import yaml

from src.agent import handler
from src.config import load_config
from src.llm import TOOL_SCHEMA


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


def load_eval_config(path: Path) -> dict:
    """Load eval YAML with models and prompts lists."""
    return yaml.safe_load(Path(path).read_text())


EVAL_SYSTEM_PROMPT = """You are a personal assistant. You have one tool: execute_bash. Use it to accomplish tasks on the user's computer. You are running on Ubuntu.

When you receive a message:
- If it requires action, use bash to accomplish it.
- If it's conversational, just reply.
- If you're unsure what the user wants, ask.

Keep replies short and direct."""


def build_agent_config(model_entry: dict, base_config: dict) -> dict:
    """Merge a model entry into the base config."""
    return {**base_config, "model": model_entry["model"]}


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
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return {c["name"]: {"score": 0.0, "reasoning": "Judge returned invalid JSON"} for c in criteria}


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
