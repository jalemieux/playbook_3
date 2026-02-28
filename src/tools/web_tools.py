"""Web-oriented tool schemas and executors."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from src.tools.utils import to_json

WEB_FETCH_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "WebFetch",
        "description": (
            "Fetch and extract content from a specific URL. "
            "Use when you already know the target page."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Fully-qualified URL to fetch.",
                },
                "prompt": {
                    "type": "string",
                    "description": "What information to extract or summarize from the page.",
                },
            },
            "required": ["url", "prompt"],
        },
    },
}

WEB_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "WebSearch",
        "description": (
            "Search the public web for current information. "
            "Use before WebFetch when no specific URL is known."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "allowed_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Only include results from these domains.",
                },
                "blocked_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Exclude results from these domains.",
                },
            },
            "required": ["query"],
        },
    },
}


def _extract_text_from_html(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def exec_web_fetch(args: dict[str, Any], config: dict, status_fn=None) -> str:
    req = Request(args["url"], headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Error fetching URL: {e}"

    return to_json(
        {
            "url": args["url"],
            "prompt": args.get("prompt", ""),
            "content": _extract_text_from_html(body)[:3000],
        }
    )


def exec_web_search(args: dict[str, Any], config: dict, status_fn=None) -> str:
    url = f"https://duckduckgo.com/html/?q={quote_plus(args['query'])}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Error searching web: {e}"

    matches = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html)
    results = []
    for href, title in matches[:8]:
        results.append({"title": re.sub("<[^>]+>", "", title), "url": href})
    return to_json({"query": args["query"], "results": results})
