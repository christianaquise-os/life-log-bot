import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import TELEGRAM_ALLOWED_CHAT_ID, TELEGRAM_BOT_TOKEN
from src.digest import build_digest
from src.flows import route_message

logger = logging.getLogger(__name__)


def _allowed(chat_id: int) -> bool:
    return chat_id == TELEGRAM_ALLOWED_CHAT_ID


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    text = update.message.text
    reply = await asyncio.to_thread(route_message, chat_id, text, update.message.message_id)
    await update.message.reply_text(reply)


async def on_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    reply = await asyncio.to_thread(build_digest, chat_id)
    await update.message.reply_text(reply)


def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("today", on_today))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return app
