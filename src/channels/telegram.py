import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from src.orchestrator import handler

logger = logging.getLogger(__name__)


async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming Telegram message."""
    config = context.bot_data["config"]
    text = update.message.text
    if not text:
        return

    def reply_fn(response: str):
        # Schedule the async reply from sync context
        import asyncio
        asyncio.get_event_loop().call_soon_threadsafe(
            asyncio.ensure_future,
            update.message.reply_text(response),
        )

    # Run agent in thread to avoid blocking the event loop
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, handler, text, reply_fn, config, str(update.message.chat_id))


def start_telegram(config: dict) -> None:
    """Start Telegram bot polling."""
    app = ApplicationBuilder().token(config["telegram_bot_token"]).build()
    app.bot_data["config"] = config
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))
    logger.info("Telegram bot started")
    app.run_polling()
