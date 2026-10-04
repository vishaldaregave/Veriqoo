"""Repository abstractions and implementations for Telegram Account Links."""

from __future__ import annotations

import abc
from datetime import datetime, timezone
import logging
import threading
from typing import Any
import uuid

import requests

from backend.app.config import Settings, get_settings
from backend.app.telegram.account_linking.models import (
    AccountLink,
    AccountLinkStatus,
    LinkChallenge,
)

logger = logging.getLogger(__name__)


class AccountLinkRepository(abc.ABC):
    """Abstract repository for persisting verified account links and link challenges."""

    @abc.abstractmethod
    def get_active_link(self, telegram_user_id: int) -> AccountLink | None:
        """Retrieve active account link for a Telegram user, or None."""
        pass

    @abc.abstractmethod
    def get_active_link_by_supabase_user(self, supabase_user_id: str) -> AccountLink | None:
        """Retrieve active account link for a Supabase user, or None."""
        pass

    @abc.abstractmethod
    def save_link(self, link: AccountLink) -> AccountLink:
        """Persist or update an AccountLink record."""
        pass

    @abc.abstractmethod
    def revoke_link(self, telegram_user_id: int) -> bool:
        """Revoke active account link for a Telegram user."""
        pass

    @abc.abstractmethod
    def save_challenge(self, challenge: LinkChallenge) -> None:
        """Persist a one-time link challenge token."""
        pass

    @abc.abstractmethod
    def get_challenge_by_token_hash(self, token_hash: str) -> LinkChallenge | None:
        """Lookup challenge by its SHA-256 hash."""
        pass

    @abc.abstractmethod
    def mark_challenge_consumed(self, challenge_id: str) -> None:
        """Mark challenge token as consumed."""
        pass


class InMemoryAccountLinkRepository(AccountLinkRepository):
    """Thread-safe in-memory repository for account linking in unit and integration tests."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._links_by_tg: dict[int, AccountLink] = {}
        self._challenges_by_hash: dict[str, LinkChallenge] = {}

    def get_active_link(self, telegram_user_id: int) -> AccountLink | None:
        with self._lock:
            link = self._links_by_tg.get(telegram_user_id)
            if link and link.is_active:
                return link
            return None

    def get_active_link_by_supabase_user(self, supabase_user_id: str) -> AccountLink | None:
        with self._lock:
            for link in self._links_by_tg.values():
                if link.supabase_user_id == supabase_user_id and link.is_active:
                    return link
            return None

    def save_link(self, link: AccountLink) -> AccountLink:
        with self._lock:
            # If another active link exists for this Supabase user, revoke it first to preserve 1-to-1 mapping
            for existing in list(self._links_by_tg.values()):
                if existing.supabase_user_id == link.supabase_user_id and existing.telegram_user_id != link.telegram_user_id and existing.is_active:
                    existing.status = AccountLinkStatus.REVOKED
                    existing.updated_at = datetime.now(timezone.utc)

            self._links_by_tg[link.telegram_user_id] = link
            return link

    def revoke_link(self, telegram_user_id: int) -> bool:
        with self._lock:
            if telegram_user_id in self._links_by_tg:
                link = self._links_by_tg[telegram_user_id]
                if link.is_active:
                    link.status = AccountLinkStatus.REVOKED
                    link.updated_at = datetime.now(timezone.utc)
                    return True
            return False

    def save_challenge(self, challenge: LinkChallenge) -> None:
        with self._lock:
            self._challenges_by_hash[challenge.token_hash] = challenge

    def get_challenge_by_token_hash(self, token_hash: str) -> LinkChallenge | None:
        with self._lock:
            return self._challenges_by_hash.get(token_hash)

    def mark_challenge_consumed(self, challenge_id: str) -> None:
        with self._lock:
            for ch in self._challenges_by_hash.values():
                if ch.challenge_id == challenge_id:
                    ch.consumed = True
                    break

    def clear(self) -> None:
        with self._lock:
            self._links_by_tg.clear()
            self._challenges_by_hash.clear()


class SupabaseAccountLinkRepository(AccountLinkRepository):
    """PostgreSQL / Supabase implementation for persistent account linking."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = f"{self.settings.supabase_url.rstrip('/')}/rest/v1"
        self._in_memory_challenges: dict[str, LinkChallenge] = {}
        self._challenge_lock = threading.RLock()

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        h = {
            "apikey": self.settings.supabase_service_role_key or self.settings.supabase_anon_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key or self.settings.supabase_anon_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    def _request(self, method: str, table: str, **kwargs: Any) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{table}"
        resp = requests.request(method, url, timeout=10, **kwargs)
        if resp.status_code >= 400:
            logger.error("Supabase API error %d on %s %s: %s", resp.status_code, method, url, resp.text)
            resp.raise_for_status()
        if not resp.text or resp.text.strip() == "":
            return []
        try:
            data = resp.json()
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def get_active_link(self, telegram_user_id: int) -> AccountLink | None:
        rows = self._request(
            "get",
            "telegram_account_links",
            headers=self._headers(),
            params={"telegram_user_id": f"eq.{telegram_user_id}", "status": "eq.ACTIVE", "limit": "1"},
        )
        if not rows:
            return None
        r = rows[0]
        return AccountLink(
            id=str(r["id"]),
            telegram_user_id=int(r["telegram_user_id"]),
            supabase_user_id=str(r["supabase_user_id"]),
            status=AccountLinkStatus(r["status"]),
            linked_at=datetime.fromisoformat(r["linked_at"].replace("Z", "+00:00")),
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
        )

    def get_active_link_by_supabase_user(self, supabase_user_id: str) -> AccountLink | None:
        rows = self._request(
            "get",
            "telegram_account_links",
            headers=self._headers(),
            params={"supabase_user_id": f"eq.{supabase_user_id}", "status": "eq.ACTIVE", "limit": "1"},
        )
        if not rows:
            return None
        r = rows[0]
        return AccountLink(
            id=str(r["id"]),
            telegram_user_id=int(r["telegram_user_id"]),
            supabase_user_id=str(r["supabase_user_id"]),
            status=AccountLinkStatus(r["status"]),
            linked_at=datetime.fromisoformat(r["linked_at"].replace("Z", "+00:00")),
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
        )

    def save_link(self, link: AccountLink) -> AccountLink:
        # 1. Revoke any existing active link for this Supabase user
        existing = self.get_active_link_by_supabase_user(link.supabase_user_id)
        if existing and existing.telegram_user_id != link.telegram_user_id:
            self.revoke_link(existing.telegram_user_id)

        # 2. Upsert link record
        payload = {
            "telegram_user_id": link.telegram_user_id,
            "supabase_user_id": link.supabase_user_id,
            "status": link.status.value,
            "linked_at": link.linked_at.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        res = self._request(
            "post",
            "telegram_account_links",
            headers=self._headers(prefer="resolution=merge-duplicates,return=representation"),
            json=payload,
        )
        if res:
            r = res[0]
            link.id = str(r["id"])
        return link

    def revoke_link(self, telegram_user_id: int) -> bool:
        res = self._request(
            "patch",
            "telegram_account_links",
            headers=self._headers(prefer="return=representation"),
            params={"telegram_user_id": f"eq.{telegram_user_id}", "status": "eq.ACTIVE"},
            json={"status": "REVOKED", "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        return len(res) > 0

    def save_challenge(self, challenge: LinkChallenge) -> None:
        with self._challenge_lock:
            self._in_memory_challenges[challenge.token_hash] = challenge

    def get_challenge_by_token_hash(self, token_hash: str) -> LinkChallenge | None:
        with self._challenge_lock:
            return self._in_memory_challenges.get(token_hash)

    def mark_challenge_consumed(self, challenge_id: str) -> None:
        with self._challenge_lock:
            for ch in self._in_memory_challenges.values():
                if ch.challenge_id == challenge_id:
                    ch.consumed = True
                    break

