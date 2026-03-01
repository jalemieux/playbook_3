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
