"""Business domain service for managing Telegram account linking workflows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
import uuid

from backend.app.auth.models import AuthenticatedUser
from backend.app.telegram.account_linking.models import (
    AccountLink,
    AccountLinkStatus,
    LinkChallenge,
)
from backend.app.telegram.account_linking.repository import (
    AccountLinkRepository,
    InMemoryAccountLinkRepository,
)

logger = logging.getLogger(__name__)


class AccountLinkError(Exception):
    """Base exception for account linking errors."""
    pass


class InvalidLinkTokenError(AccountLinkError):
    """Raised when link token is malformed, unrecognized, or invalid."""
    pass


class ExpiredLinkTokenError(AccountLinkError):
    """Raised when link challenge has expired."""
    pass


class ConsumedLinkTokenError(AccountLinkError):
    """Raised when link challenge was already consumed."""
    pass


class AccountLinkingService:
    """Service handling cryptographic challenge token issuance and authenticated link consumption."""

    def __init__(self, repository: AccountLinkRepository | None = None) -> None:
        self.repository = repository or InMemoryAccountLinkRepository()

    def _hash_token(self, token: str) -> str:
        """Compute SHA-256 hash of plaintext link token."""
        return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

    def create_link_challenge(
        self,
        telegram_user_id: int,
        ttl_seconds: int = 600,
    ) -> tuple[str, datetime]:
        """Generate high-entropy one-time link token bound to telegram_user_id.

        Returns (raw_plaintext_token, expiration_datetime).
        Raw token is never persisted—only its SHA-256 hash is stored.
        """
        raw_token = f"vlink_{secrets.token_urlsafe(32)}"
        token_hash = self._hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        challenge = LinkChallenge(
            challenge_id=str(uuid.uuid4()),
            telegram_user_id=telegram_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            consumed=False,
        )
        self.repository.save_challenge(challenge)
        return raw_token, expires_at

    def consume_link_challenge(
        self,
        token: str,
        authenticated_user: AuthenticatedUser,
    ) -> AccountLink:
        """Consume one-time link challenge and establish verified link to authenticated_user.

        Guarantees:
        1. Authenticated user identity comes strictly from validated Supabase JWT context.
        2. Token must exist, match hash, be unexpired, and unconsumed.
        3. Token is immediately marked consumed to prevent replay.
        4. Creates or updates AccountLink record.
        """
        if not token or not isinstance(token, str) or token.strip() == "":
            raise InvalidLinkTokenError("Link token is missing or empty.")

        if not authenticated_user or not authenticated_user.user_id:
            raise AccountLinkError("Authenticated user context is required to link an account.")

        token_hash = self._hash_token(token)
        challenge = self.repository.get_challenge_by_token_hash(token_hash)

        if challenge is None:
            raise InvalidLinkTokenError("Invalid or unrecognized account link token.")

        if challenge.consumed:
            raise ConsumedLinkTokenError("This account link token has already been consumed.")

        if challenge.is_expired:
            raise ExpiredLinkTokenError("This account link token has expired. Please request a new one via /link.")

        # Invalidate token immediately
        self.repository.mark_challenge_consumed(challenge.challenge_id)

        # Create or update active link
        now = datetime.now(timezone.utc)
        link = AccountLink(
            id=str(uuid.uuid4()),
            telegram_user_id=challenge.telegram_user_id,
            supabase_user_id=authenticated_user.user_id,
            status=AccountLinkStatus.ACTIVE,
            linked_at=now,
            created_at=now,
            updated_at=now,
        )
        saved_link = self.repository.save_link(link)
        logger.info(
            "Successfully linked Telegram user %d to Supabase user %s",
            challenge.telegram_user_id,
            authenticated_user.user_id,
        )
        return saved_link

    def unlink_account(self, telegram_user_id: int) -> bool:
        """Revoke active account link for a Telegram user."""
        return self.repository.revoke_link(telegram_user_id)

    def get_linked_user(self, telegram_user_id: int) -> AccountLink | None:
        """Retrieve active AccountLink for a Telegram user."""
        return self.repository.get_active_link(telegram_user_id)

