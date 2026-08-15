import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import TELEGRAM_ALLOWED_CHAT_ID, TELEGRAM_BOT_TOKEN
from src.digest import build_digest
from src.flows import route_message
from src.habits import create_habit, list_habits, log_habit
from src.mood import log_mood

logger = logging.getLogger(__name__)

FAILURE_REPLY = "Something went wrong processing that — try again in a moment."


def _allowed(chat_id: int) -> bool:
    return chat_id == TELEGRAM_ALLOWED_CHAT_ID


def _message_sent_at(update: Update) -> str:
    return update.message.date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    text = update.message.text
    message_sent_at = _message_sent_at(update)
    try:
        reply = await asyncio.to_thread(
            route_message, chat_id, text, update.message.message_id, message_sent_at
        )
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


async def on_mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    args_text = " ".join(context.args) if context.args else ""
    try:
        reply = await asyncio.to_thread(log_mood, chat_id, args_text, _message_sent_at(update))
    except Exception:
        logger.exception("log_mood failed for chat_id=%s", chat_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_newhabit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    name = " ".join(context.args) if context.args else ""
    try:
        reply = await asyncio.to_thread(create_habit, chat_id, name)
    except Exception:
        logger.exception("create_habit failed for chat_id=%s", chat_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_log_habit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    name_query = " ".join(context.args) if context.args else ""
    try:
        reply = await asyncio.to_thread(log_habit, chat_id, name_query, _message_sent_at(update))
    except Exception:
        logger.exception("log_habit failed for chat_id=%s", chat_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_habits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    try:
        reply = await asyncio.to_thread(list_habits, chat_id)
    except Exception:
        logger.exception("list_habits failed for chat_id=%s", chat_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception while processing update %s", update, exc_info=context.error)


def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("today", on_today))
    app.add_handler(CommandHandler("mood", on_mood))
    app.add_handler(CommandHandler("newhabit", on_newhabit))
    app.add_handler(CommandHandler("log", on_log_habit))
    app.add_handler(CommandHandler("habits", on_habits))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_error_handler(on_error)
    return app
