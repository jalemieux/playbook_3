# Background Notifier Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a background daemon thread that periodically puts a system message on the notification queue so the CLI receives it; placeholder behavior only.

**Architecture:** New `src/background.py` with `start_background_notifier(queue, interval_sec=60, message="...")` that starts one daemon thread. `main.py` calls it after creating the queue and before `run_cli`. Message shape: `{"role": "system", "content": "..."}` so existing CLI handling works.

**Tech Stack:** Python stdlib `threading`, `queue` (already used in main/cli).

**Design doc:** `docs/plans/2026-03-01-background-notifier-design.md`

---

### Task 1: Add `src/background.py` and failing test

**Files:**
- Create: `src/background.py`
- Create: `tests/test_background.py`

**Step 1: Write the failing test**

In `tests/test_background.py`:

```python
import queue
import time
from src.background import start_background_notifier

def test_notifier_puts_system_message_on_queue():
    q = queue.Queue()
    start_background_notifier(q, interval_sec=0.1, message="ping")
    time.sleep(0.25)  # allow 2 ticks
    msgs = []
    while True:
        try:
            msgs.append(q.get_nowait())
        except queue.Empty:
            break
    assert len(msgs) >= 1
    for m in msgs:
        assert m.get("role") == "system"
        assert "ping" in m.get("content", "")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_background.py -v`

Expected: FAIL (e.g. module or function not found).

**Step 3: Write minimal implementation**

In `src/background.py`:

```python
import queue
import threading
import time

def start_background_notifier(
    notification_queue: queue.Queue,
    interval_sec: float = 60,
    message: str = "Background ping (placeholder).",
) -> None:
    def _run() -> None:
        while True:
            time.sleep(interval_sec)
            notification_queue.put({"role": "system", "content": message})

    t = threading.Thread(target=_run, daemon=True)
    t.start()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_background.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/background.py tests/test_background.py
git commit -m "feat: add background notifier module with placeholder system messages"
```

---

### Task 2: Wire notifier in main.py (CLI only)

**Files:**
- Modify: `main.py`

**Step 1: Add import and call**

At top with other imports, add:

```python
from src.background import start_background_notifier
```

After the line that creates `notification_queue` (and before the `if args.channel == "cli":` block), add:

```python
start_background_notifier(notification_queue, interval_sec=60)
```

So the block looks like:

```python
    notification_queue: queue.Queue[str | object] = queue.Queue()
    start_background_notifier(notification_queue, interval_sec=60)

    if args.channel == "cli":
```

**Step 2: Run tests**

Run: `pytest tests/test_background.py -v`

Expected: PASS.

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: start background notifier when running CLI"
```

---

### Task 3: Manual smoke check (no code change)

**Step 1:** Run CLI: `python main.py --channel cli --agent <your-agent>` (or default agent).

**Step 2:** Wait ~60 seconds without typing. A system message should appear as if the user had sent it (agent processes it). Optional: reduce `interval_sec` in the call (e.g. to 10) for faster check.

**Step 3:** If desired, revert interval to 60 and commit, or leave as-is.

---

## Execution handoff

Plan complete and saved to `docs/plans/2026-03-01-background-notifier.md`.

Two execution options:

1. **Subagent-driven (this session)** — I run each task (test first, implement, commit), you review between tasks.
2. **Parallel session** — You open a new session in this repo (or worktree), paste the plan, and use executing-plans there.

Which approach do you want?
