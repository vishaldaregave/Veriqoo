"""Phase 9E Telegram Bot Integration for Veriqoo."""

from __future__ import annotations

from backend.app.telegram.adapter import TelegramBotAdapter
from backend.app.telegram.bot import build_telegram_application, create_telegram_bot_handlers
from backend.app.telegram.formatter import (
    format_help_message,
    format_inspection_report,
    format_inspection_status,
    format_safe_error,
    format_welcome_message,
    sanitize_telegram_text,
)
from backend.app.telegram.identity import (
    DeterministicTelegramIdentityProvider,
    ExplicitMappingTelegramIdentityProvider,
    TELEGRAM_IDENTITY_NAMESPACE,
    TelegramIdentityProvider,
)
from backend.app.telegram.models import (
    TelegramConversation,
    TelegramUserIdentity,
    TelegramWorkflowState,
)

__all__ = [
    "DeterministicTelegramIdentityProvider",
    "ExplicitMappingTelegramIdentityProvider",
    "TELEGRAM_IDENTITY_NAMESPACE",
    "TelegramBotAdapter",
    "TelegramConversation",
    "TelegramIdentityProvider",
    "TelegramUserIdentity",
    "TelegramWorkflowState",
    "build_telegram_application",
    "create_telegram_bot_handlers",
    "format_help_message",
    "format_inspection_report",
    "format_inspection_status",
    "format_safe_error",
    "format_welcome_message",
    "sanitize_telegram_text",
]

