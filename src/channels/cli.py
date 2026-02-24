from src.agent import handler


def run_cli(config: dict) -> None:
    """Interactive CLI for testing the agent."""
    print("Agent CLI (type 'quit' to exit)")
    while True:
        try:
            text = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.strip().lower() in ("quit", "exit"):
            break
        handler(text, print, config)
