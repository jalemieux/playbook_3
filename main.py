import argparse
import logging
import os
import queue
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.config import load_config
from src.agents.factory import create_agent_one
from src.background import start_background_notifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

# Map PB3_* env vars to the standard names LiteLLM expects
os.environ["ANTHROPIC_API_KEY"] = os.environ["PB3_ANTHROPIC_API_KEY"]
os.environ["OPENAI_API_KEY"] = os.environ["PB3_OPENAI_API_KEY"]
os.environ["GEMINI_API_KEY"] = os.environ["PB3_GEMINI_API_KEY"]
os.environ["MINIMAX_API_KEY"] = os.environ["PB3_MINIMAX_API_KEY"]


def main():
    config = load_config(Path("config.yaml"))
    parser = argparse.ArgumentParser(description="Minimal agent")
    parser.add_argument("--channel", choices=["cli", "telegram", "gmail", "all"],
                        default=os.environ.get("CHANNEL", "all"))
    parser.add_argument("--agent", choices=list(config.get("agent_profiles", {}).keys()))
    args = parser.parse_args()

    # load agent profile from config
    agent_cfg = config.get("agent_profiles", {}).get(args.agent) or {}

    # agent factory creates agent instance
    agent = create_agent_one(
        model=agent_cfg.get("model"),
        max_iterations=agent_cfg.get("max_iterations", 10),
        context_dir_path=agent_cfg.get("context_dir_path"),   
        identity_file_path=agent_cfg.get("identity_file_path"),
        name=args.agent)

    # system notification (e.g. you got a new email)
    notification_queue: queue.Queue[str | object] = queue.Queue()
    start_background_notifier(notification_queue, interval_sec=60)

    if args.channel == "cli":
        from src.channels.cli import run_cli
        run_cli(agent, config, notification_queue)
    # elif args.channel == "telegram":
    #     from src.channels.telegram import start_telegram
    #     start_telegram(config)
    # elif args.channel == "gmail":
    #     from src.channels.gmail import start_gmail
    #     start_gmail(config)
    # else:
    #     # Run telegram + gmail together (CLI not included in "all")
    #     import threading
    #     from src.channels.telegram import start_telegram
    #     from src.channels.gmail import start_gmail
    #     gmail_thread = threading.Thread(target=start_gmail, args=(config,), daemon=True)
    #     gmail_thread.start()
    #     start_telegram(config)  # Blocks (runs its own event loop)


if __name__ == "__main__":
    main()
