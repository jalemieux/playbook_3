import readline
import sys
import threading
import time

from src.agents import get_agent, get_clear_session

DIM = "\033[2m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"

# State
_verbose = False


def _format_call(text: str, max_len: int = 80) -> str:
    """Collapse multiline commands to a single truncated line."""
    if not text:
        return "?"
    one_line = text.replace("\n", " ").replace("  ", " ")
    if len(one_line) <= max_len:
        return one_line
    return one_line[:max_len] + "…"


class _Spinner:
    """Inline spinner that overwrites itself on the same line."""
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()
        # Clear the spinner line
        sys.stdout.write(f"\r\033[2K")
        sys.stdout.flush()

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stdout.write(f"\r  {DIM}{frame} thinking…{RESET}")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)


def _make_status_fn():
    """Create a status callback that respects current verbose mode."""
    spinner = _Spinner()

    def _status(kind: str, text: str) -> None:
        if kind == "thinking":
            spinner.start()
        elif kind == "done_thinking":
            spinner.stop()
        elif kind == "tool_call":
            if _verbose:
                print(f"  {DIM}╭─{RESET} {YELLOW}▶ {_format_call(text)}{RESET}")
            else:
                _status._pending_call = text
        elif kind == "tool_result":
            lines = text.splitlines()
            if _verbose:
                for i, line in enumerate(lines):
                    connector = "╰─" if i == len(lines) - 1 else "│ "
                    print(f"  {DIM}│ {connector} {line}{RESET}")
                print()
            else:
                call = _format_call(getattr(_status, "_pending_call", "?"))
                n = len(lines)
                summary = f"{n} line{'s' if n != 1 else ''}"
                print(f"  {DIM}│{RESET} {DIM}╭─{RESET} {YELLOW}▶ {call}{RESET} {DIM}→ {summary}{RESET}")
                _status._pending_call = None
        elif kind == "sub_agent_call":
            if _verbose:
                print(f"  {DIM}╭─{RESET} {YELLOW}▶ Sub-Agent({RESET}\"{text}\"{YELLOW}){RESET}")
            else:
                print(f"  {DIM}╭─{RESET} {YELLOW}▶ Sub-Agent({RESET}\"{_format_call(text)}\"{YELLOW}){RESET}")
        elif kind == "sub_agent_result":
            lines = text.splitlines()
            n = len(lines)
            summary = f"{n} line{'s' if n != 1 else ''}"
            print(f"  {DIM}╰─ → {summary}{RESET}")
    return _status


def _reply(text: str) -> None:
    print(f"{CYAN}{text}{RESET}")
    print()


def run_cli(config: dict) -> None:
    """Interactive CLI for testing the agent."""
    global _verbose

    agent_name = config.get("agent", "orchestrator")
    agent_handler = get_agent(agent_name)
    agent_clear = get_clear_session(agent_name)

    mode = f"{DIM}collapsed{RESET}" if not _verbose else f"{DIM}expanded{RESET}"
    print(f"{BOLD}Agent CLI{RESET}  {DIM}ctrl+e: toggle tool output | /clear: reset | 'quit' to exit{RESET}")
    print(f"  {DIM}agent:        {RESET}{agent_name}")
    model_keys = {"base": "base_model", "orchestrator": "orchestrator_model", "single": "agent_model"}
    model = config.get(model_keys.get(agent_name, "agent_model"), "unknown")
    print(f"  {DIM}model:        {RESET}{model}")
    print(f"  {DIM}tool output:  {RESET}{mode}")
    print()

    while True:
        try:
            text = input(f"{GREEN}> {RESET}")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = text.strip().lower()
        if stripped in ("quit", "exit"):
            break

        if stripped == "\x05" or stripped == "/verbose" or stripped == "/v":
            _verbose = not _verbose
            mode_label = "expanded" if _verbose else "collapsed"
            print(f"  {DIM}tool output: {mode_label}{RESET}")
            print()
            continue

        if stripped in ("/clear", "/reset"):
            agent_clear("cli")
            print(f"  {DIM}conversation cleared{RESET}")
            print()
            continue

        agent_handler(text, _reply, config, session_id="cli", status_fn=_make_status_fn())
