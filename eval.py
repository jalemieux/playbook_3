"""Lightweight eval framework — run prompts across models, compare results."""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import yaml

from src.agent import handler
from src.config import load_config


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
