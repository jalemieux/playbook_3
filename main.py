import argparse
import logging
import os
from pathlib import Path

from src.config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="Minimal agent")
    parser.add_argument("--channel", choices=["cli", "telegram", "gmail", "all"],
                        default=os.environ.get("CHANNEL", "all"))
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config(Path(args.config))

    if args.channel == "cli":
        from src.channels.cli import run_cli
        run_cli(config)
    elif args.channel == "telegram":
        from src.channels.telegram import start_telegram
        start_telegram(config)
    elif args.channel == "gmail":
        from src.channels.gmail import start_gmail
        start_gmail(config)
    else:
        # Run telegram + gmail together (CLI not included in "all")
        import threading
        from src.channels.telegram import start_telegram
        from src.channels.gmail import start_gmail
        gmail_thread = threading.Thread(target=start_gmail, args=(config,), daemon=True)
        gmail_thread.start()
        start_telegram(config)  # Blocks (runs its own event loop)


if __name__ == "__main__":
    main()
