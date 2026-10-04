"""Phase 9E-A Telegram Account Linking module."""

from __future__ import annotations

from backend.app.telegram.account_linking.models import (
    AccountLink,
    AccountLinkStatus,
    LinkChallenge,
)
from backend.app.telegram.account_linking.repository import (
    AccountLinkRepository,
    InMemoryAccountLinkRepository,
    SupabaseAccountLinkRepository,
)
from backend.app.telegram.account_linking.service import (
    AccountLinkError,
    AccountLinkingService,
    ConsumedLinkTokenError,
    ExpiredLinkTokenError,
    InvalidLinkTokenError,
)

__all__ = [
    "AccountLink",
    "AccountLinkError",
    "AccountLinkRepository",
    "AccountLinkStatus",
    "AccountLinkingService",
    "ConsumedLinkTokenError",
    "ExpiredLinkTokenError",
    "InMemoryAccountLinkRepository",
    "InvalidLinkTokenError",
    "LinkChallenge",
    "SupabaseAccountLinkRepository",
]

