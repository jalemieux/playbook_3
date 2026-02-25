import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from src.agent import handler

logger = logging.getLogger(__name__)


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
    await loop.run_in_executor(None, handler, text, reply_fn, config)


def start_telegram(config: dict) -> None:
    """Start Telegram bot polling."""
    app = ApplicationBuilder().token(config["telegram_bot_token"]).build()
    app.bot_data["config"] = config
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))
    logger.info("Telegram bot started")
    app.run_polling()
