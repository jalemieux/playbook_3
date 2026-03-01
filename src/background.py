import queue
import random
import threading
import time

def start_background_notifier(
    notification_queue: queue.Queue,
    interval_sec: float = 10,
) -> None:
    def _run() -> None:
        messages = [ "user has a new email in their inbox.",
        "generate a new report for the user", 
        "reminder for x fired off "]
        message = "User received a new email from CFO marked urgent."
        while True:
            time.sleep(interval_sec)
            notification_queue.put({"role": "assistant", "content": "system notification: " + message})

    t = threading.Thread(target=_run, daemon=True)
    t.start()
