import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import TELEGRAM_ALLOWED_CHAT_ID, TELEGRAM_BOT_TOKEN
from src.digest import build_digest
from src.flows import route_message
from src.habits import create_habit, list_habits, log_habit
from src.mood import log_mood
from src.movies import add_movie, list_watchlist, mark_watched
from src.receipts import handle_receipt_photo

logger = logging.getLogger(__name__)

FAILURE_REPLY = "Something went wrong processing that — try again in a moment."

HELP_TEXT = (
    "Things you can say:\n"
    '- "started X" / "I\'m done" / "did X for 30 min" — activity logging\n'
    '- "how did I do today" or /today — daily summary\n'
    "- send a photo of a receipt — logs it as an expense\n\n"
    "Commands:\n"
    "/today — today's digest\n"
    "/mood <score 1-10> [note] — log a mood check-in\n"
    "/newhabit <name> — create a habit\n"
    "/log <habit> — log today's completion\n"
    "/habits — list habits and streaks\n"
    "/addmovie <title> — add to watchlist (needs OMDB_API_KEY)\n"
    "/watched <title> [rating] — mark a movie watched\n"
    "/watchlist — list movies to watch\n"
    "/help — this message"
)


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


async def on_addmovie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    title = " ".join(context.args) if context.args else ""
    try:
        reply = await asyncio.to_thread(add_movie, chat_id, title)
    except Exception:
        logger.exception("add_movie failed for chat_id=%s", chat_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_watched(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    args = context.args or []
    rating = None
    title_parts = args
    if args and args[-1].isdigit():
        rating = int(args[-1])
        title_parts = args[:-1]
    title_query = " ".join(title_parts)
    try:
        reply = await asyncio.to_thread(mark_watched, chat_id, title_query, rating)
    except Exception:
        logger.exception("mark_watched failed for chat_id=%s", chat_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    try:
        reply = await asyncio.to_thread(list_watchlist, chat_id)
    except Exception:
        logger.exception("list_watchlist failed for chat_id=%s", chat_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    photo = update.message.photo[-1]  # largest available size
    caption = update.message.caption
    message_sent_at = _message_sent_at(update)
    try:
        file = await context.bot.get_file(photo.file_id)
        image_bytes = bytes(await file.download_as_bytearray())
        reply = await asyncio.to_thread(
            handle_receipt_photo, chat_id, image_bytes, "image/jpeg", photo.file_id, caption, message_sent_at
        )
    except Exception:
        logger.exception("receipt photo handling failed for chat_id=%s", chat_id)
        await update.message.reply_text(FAILURE_REPLY)
        return
    await update.message.reply_text(reply)


async def on_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not _allowed(chat_id):
        return
    await update.message.reply_text(HELP_TEXT)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception while processing update %s", update, exc_info=context.error)


def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("help", on_help))
    app.add_handler(CommandHandler("today", on_today))
    app.add_handler(CommandHandler("mood", on_mood))
    app.add_handler(CommandHandler("newhabit", on_newhabit))
    app.add_handler(CommandHandler("log", on_log_habit))
    app.add_handler(CommandHandler("habits", on_habits))
    app.add_handler(CommandHandler("addmovie", on_addmovie))
    app.add_handler(CommandHandler("watched", on_watched))
    app.add_handler(CommandHandler("watchlist", on_watchlist))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_error_handler(on_error)
    return app
