import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import TELEGRAM_ALLOWED_CHAT_ID, TELEGRAM_BOT_TOKEN
from src.digest import build_digest
from src.flows import route_message

logger = logging.getLogger(__name__)

FAILURE_REPLY = "Something went wrong processing that — try again in a moment."


def _allowed(chat_id: int) -> bool:
    return chat_id == TELEGRAM_ALLOWED_CHAT_ID


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    text = update.message.text
    try:
        reply = await asyncio.to_thread(route_message, chat_id, text, update.message.message_id)
    except Exception:
        logger.exception("route_message failed for chat_id=%s message_id=%s", chat_id, update.message.message_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    try:
        reply = await asyncio.to_thread(build_digest, chat_id)
    except Exception:
        logger.exception("build_digest failed for chat_id=%s", chat_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception while processing update %s", update, exc_info=context.error)


def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("today", on_today))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_error_handler(on_error)
    return app
