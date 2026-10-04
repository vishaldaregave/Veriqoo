"""Python-Telegram-Bot wrapper and application factory for Veriqoo."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from backend.app.telegram.adapter import TelegramBotAdapter
from backend.app.telegram.models import TelegramUserIdentity

logger = logging.getLogger(__name__)


def _extract_identity(update: Update) -> TelegramUserIdentity | None:
    """Extract structured TelegramUserIdentity from incoming Update."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return None
    return TelegramUserIdentity(
        telegram_user_id=user.id,
        chat_id=chat.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )


def create_telegram_bot_handlers(adapter: TelegramBotAdapter) -> list[Any]:
    """Create list of python-telegram-bot command and message handlers."""

    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if identity and update.message:
            reply = adapter.handle_start(identity)
            await update.message.reply_text(reply, parse_mode="Markdown")

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if identity and update.message:
            reply = adapter.handle_help(identity)
            await update.message.reply_text(reply, parse_mode="Markdown")

    async def link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if identity and update.message:
            reply = adapter.handle_link(identity)
            await update.message.reply_text(reply, parse_mode="Markdown")

    async def unlink_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if identity and update.message:
            reply = adapter.handle_unlink(identity)
            await update.message.reply_text(reply, parse_mode="Markdown")

    async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if identity and update.message:
            reply = adapter.handle_new(identity)
            await update.message.reply_text(reply, parse_mode="Markdown")

    async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if identity and update.message:
            reply = adapter.handle_run(identity)
            await update.message.reply_text(reply, parse_mode="Markdown")

    async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if identity and update.message:
            reply = adapter.handle_status(identity)
            await update.message.reply_text(reply, parse_mode="Markdown")

    async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if identity and update.message:
            reply = adapter.handle_report(identity)
            await update.message.reply_text(reply, parse_mode="Markdown")

    async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if identity and update.message:
            reply = adapter.handle_cancel(identity)
            await update.message.reply_text(reply, parse_mode="Markdown")

    async def photo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        identity = _extract_identity(update)
        if not identity or not update.message or not update.message.photo:
            return

        # Choose the largest available photo resolution
        largest_photo = update.message.photo[-1]
        try:
            tg_file = await context.bot.get_file(largest_photo.file_id)
            byte_arr = await tg_file.download_as_bytearray()
            reply = adapter.handle_photo(
                identity=identity,
                photo_bytes=bytes(byte_arr),
                filename=f"photo_{largest_photo.file_id[:8]}.jpg",
            )
            await update.message.reply_text(reply, parse_mode="Markdown")
        except Exception as exc:
            logger.exception("Error processing Telegram photo: %s", exc)
            await update.message.reply_text(
                "❌ Failed to download or process photograph. Please try sending again."
            )

    return [
        CommandHandler("start", start_cmd),
        CommandHandler("help", help_cmd),
        CommandHandler("link", link_cmd),
        CommandHandler("unlink", unlink_cmd),
        CommandHandler("new", new_cmd),
        CommandHandler("run", run_cmd),
        CommandHandler("status", status_cmd),
        CommandHandler("report", report_cmd),
        CommandHandler("cancel", cancel_cmd),
        MessageHandler(filters.PHOTO, photo_msg),
    ]


def build_telegram_application(token: str, adapter: TelegramBotAdapter) -> Application:
    """Build configured python-telegram-bot Application instance."""
    if not token or token.strip() == "":
        raise ValueError("Telegram bot token is empty or missing.")

    app = ApplicationBuilder().token(token.strip()).build()
    handlers = create_telegram_bot_handlers(adapter)
    for h in handlers:
        app.add_handler(h)
    return app

