# Background Notifier — Design

**Date:** 2026-03-01

## Goal

A background daemon thread that periodically enqueues a system message on the existing notification queue so the CLI can consume it like user input. Minimal placeholder behavior now; replace with real logic later.

## Architecture

- **New module:** `src/background.py` with a single entry point that starts one daemon thread.
- **Thread behavior:** Loop: sleep N seconds, then put `{"role": "system", "content": "<placeholder>"}` on the given queue. Daemon thread; no explicit shutdown (exits when process exits).
- **Integration:** `main.py` creates the notification queue, calls the background starter, then runs the CLI. No changes to CLI message handling (it already uses `message.get("role")` and `message.get("content")`).

## Components

| Component | Responsibility |
|-----------|----------------|
| `src/background.py` | `start_background_notifier(queue, interval_sec=60, message="...")` — starts daemon thread. |
| `main.py` | After creating `notification_queue`, call `start_background_notifier(notification_queue)` before `run_cli`. |

## Message shape

Dict with `role` and `content` so existing CLI logic works:

```python
{"role": "system", "content": "Background ping (placeholder)."}
```

## Error handling

Thread runs a simple loop; if `queue.put` ever raises, the thread will exit (daemon). No logging required for the placeholder; optional log on start if desired.

## Testing

- Unit test: start notifier with a queue and short interval, drain queue after a couple of intervals, assert received items have `role == "system"` and expected content.
- Manual: run CLI, wait for interval, confirm a system message appears as the next “input” and the agent handles it.

## Out of scope (YAGNI)

- Configurable interval/message from config file.
- Graceful stop event (daemon is enough for now).
- Multiple background tasks (single thread only).
