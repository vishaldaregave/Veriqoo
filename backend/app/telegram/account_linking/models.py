"""Domain models for Phase 9E-A Secure Telegram Account Linking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid


class AccountLinkStatus(str, Enum):
    """Lifecycle status of a Telegram-to-Supabase user account link."""
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass
class AccountLink:
    """Represents a verified relationship between a Telegram user and a Supabase Auth user."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: int = 0
    supabase_user_id: str = ""
    status: AccountLinkStatus = AccountLinkStatus.ACTIVE
    linked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        return self.status == AccountLinkStatus.ACTIVE


@dataclass
class LinkChallenge:
    """Represents a cryptographically secure, short-lived one-time challenge token."""
    challenge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    telegram_user_id: int = 0
    token_hash: str = ""
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consumed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.consumed and not self.is_expired

