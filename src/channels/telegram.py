import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from src.agents.orchestrator import handler

logger = logging.getLogger(__name__)


def _format_call(text: str, max_len: int = 120) -> str:
    """Collapse multiline commands to a single truncated line."""
    if not text:
        return "?"
    one_line = text.replace("\n", " ").replace("  ", " ")
    if len(one_line) <= max_len:
        return one_line
    return one_line[:max_len] + "…"


def _make_log_status_fn(chat_id: str):
    """Create a status callback that logs activity to container stdout."""
    def _status(kind: str, text: str) -> None:
        if kind == "thinking":
            logger.info("[%s] thinking…", chat_id)
        elif kind == "done_thinking":
            logger.info("[%s] done thinking", chat_id)
        elif kind == "tool_call":
            logger.info("[%s] ╭─ ▶ %s", chat_id, _format_call(text))
        elif kind == "tool_result":
            lines = text.splitlines()
            for i, line in enumerate(lines):
                connector = "╰─" if i == len(lines) - 1 else "│ "
                logger.info("[%s] │ %s %s", chat_id, connector, line)
        elif kind == "sub_agent_call":
            logger.info("[%s] ╭─ ▶ Sub-Agent(\"%s\")", chat_id, _format_call(text))
        elif kind == "sub_agent_result":
            n = len(text.splitlines())
            logger.info("[%s] ╰─ → %d line%s", chat_id, n, "s" if n != 1 else "")
    return _status


async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming Telegram message."""
    config = context.bot_data["config"]

    raw = config.get("telegram_allowed_users", "")
    if isinstance(raw, int):
        allowed_users = {raw}
    elif raw:
        allowed_users = {int(uid) for uid in str(raw).split(",") if uid.strip()}
    else:
        allowed_users = set()
    if allowed_users and update.effective_user.id not in allowed_users:
        logger.warning("Unauthorized Telegram user: %s (id=%s)", update.effective_user.username, update.effective_user.id)
        return

    text = update.message.text
    if not text:
        return

    # Capture the running loop before entering the thread
    import asyncio
    loop = asyncio.get_running_loop()

    def reply_fn(response: str):
        loop.call_soon_threadsafe(asyncio.ensure_future, update.message.reply_text(response))

    # Run agent in thread to avoid blocking the event loop
    chat_id = str(update.message.chat_id)
    status_fn = _make_log_status_fn(chat_id)
    logger.info("[%s] message from %s: %s", chat_id, update.effective_user.username, text[:100])
    await loop.run_in_executor(None, handler, text, reply_fn, config, chat_id, status_fn)


def start_telegram(config: dict) -> None:
    """Start Telegram bot polling."""
    app = ApplicationBuilder().token(config["telegram_bot_token"]).build()
    app.bot_data["config"] = config
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))
    logger.info("Telegram bot started")
    app.run_polling()
