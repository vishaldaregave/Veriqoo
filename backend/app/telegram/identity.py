"""Identity mapping boundary between Telegram and Veriqoo AuthenticatedUser."""

from __future__ import annotations

import abc
import uuid
from typing import Any

from backend.app.auth.models import AuthenticatedUser
from backend.app.telegram.models import TelegramUserIdentity

# Dedicated namespace UUID for deterministic Telegram user ID mapping
TELEGRAM_IDENTITY_NAMESPACE = uuid.UUID("7a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d")


class TelegramIdentityProvider(abc.ABC):
    """Abstract provider to map TelegramUserIdentity into a Veriqoo AuthenticatedUser."""

    @abc.abstractmethod
    def get_authenticated_user(self, identity: TelegramUserIdentity) -> AuthenticatedUser:
        """Map Telegram identity to an authorized Veriqoo application user."""
        pass


class DeterministicTelegramIdentityProvider(TelegramIdentityProvider):
    """Deterministic cryptographic namespace-based identity provider.

    Maps telegram_user_id into a stable, non-forgeable UUID5 subject.
    Guarantees:
    1. Telegram chat/user IDs are never directly used as raw owner_id strings.
    2. Maps to a valid UUID format compatible with the inspection ownership schema.
    3. Distinct Telegram users always receive distinct, isolated Veriqoo identities.
    """

    def __init__(self, namespace: uuid.UUID = TELEGRAM_IDENTITY_NAMESPACE) -> None:
        self.namespace = namespace

    def get_authenticated_user(self, identity: TelegramUserIdentity) -> AuthenticatedUser:
        user_uuid = uuid.uuid5(self.namespace, str(identity.telegram_user_id))
        claims = {
            "sub": str(user_uuid),
            "telegram_user_id": identity.telegram_user_id,
            "chat_id": identity.chat_id,
            "username": identity.username,
            "role": "authenticated",
        }
        email = f"tg_{identity.telegram_user_id}@telegram.veriqoo.ai"
        return AuthenticatedUser(
            user_id=str(user_uuid),
            email=email,
            role="authenticated",
            claims=claims,
        )


class ExplicitMappingTelegramIdentityProvider(TelegramIdentityProvider):
    """Allows explicit linking between Telegram user IDs and pre-existing Supabase user UUIDs."""

    def __init__(
        self,
        fallback_provider: TelegramIdentityProvider | None = None,
        initial_mappings: dict[int, str] | None = None,
    ) -> None:
        self._mappings: dict[int, str] = dict(initial_mappings or {})
        self._fallback = fallback_provider or DeterministicTelegramIdentityProvider()

    def register_mapping(self, telegram_user_id: int, supabase_user_id: str) -> None:
        self._mappings[telegram_user_id] = supabase_user_id

    def get_authenticated_user(self, identity: TelegramUserIdentity) -> AuthenticatedUser:
        if identity.telegram_user_id in self._mappings:
            supa_id = self._mappings[identity.telegram_user_id]
            return AuthenticatedUser(
                user_id=supa_id,
                email=f"linked_{identity.telegram_user_id}@veriqoo.ai",
                role="authenticated",
                claims={"sub": supa_id, "telegram_user_id": identity.telegram_user_id},
            )
        return self._fallback.get_authenticated_user(identity)

