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
